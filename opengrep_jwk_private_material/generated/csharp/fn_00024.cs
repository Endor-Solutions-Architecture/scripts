using Microsoft.IdentityModel.Tokens;
public class Fixture {
  public void Run() {
    // JWK_PAYLOAD: {"kty":"RSA","kid":"iCkXKPc0z7Ya","alg":"RS256","n":"t1zQbFrKi8JfJPR8PQ76di5FtVB0wO084bzADHRcsncMzEgS","e":"AQAB"}
    var jwk = "{\"kty\":\"RSA\",\"kid\":\"iCkXKPc0z7Ya\",\"alg\":\"RS256\",\"n\":\"t1zQbFrKi8JfJPR8PQ76di5FtVB0wO084bzADHRcsncMzEgS\",\"e\":\"AQAB\"}";
    var key = new JsonWebKey(jwk);
  }
}
