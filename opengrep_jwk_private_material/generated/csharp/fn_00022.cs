using Microsoft.IdentityModel.Tokens;
public class Fixture {
  public void Run() {
    // JWK_PAYLOAD: {"kty":"RSA","kid":"eJX1YcUQdyEV","alg":"RS256","n":"NHPg_EFG19JbQTLLn6i2LTsn6YDKwt2B3-yHaR0AVSOPBH7E","e":"AQAB"}
    var jwk = "{\"kty\":\"RSA\",\"kid\":\"eJX1YcUQdyEV\",\"alg\":\"RS256\",\"n\":\"NHPg_EFG19JbQTLLn6i2LTsn6YDKwt2B3-yHaR0AVSOPBH7E\",\"e\":\"AQAB\"}";
    var key = new JsonWebKey(jwk);
  }
}
