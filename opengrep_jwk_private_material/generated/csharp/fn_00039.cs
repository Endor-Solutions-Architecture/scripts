using Microsoft.IdentityModel.Tokens;
public class Fixture {
  public void Run() {
    // JWK_PAYLOAD: {"kty":"RSA","kid":"vyjO726E1dPP","alg":"RS256","n":"UQxpSRUdlhkCiozF99azYKGkohNhsXJuK2pQS32c-I2PW8Wu","e":"AQAB"}
    var jwk = "{\"kty\":\"RSA\",\"kid\":\"vyjO726E1dPP\",\"alg\":\"RS256\",\"n\":\"UQxpSRUdlhkCiozF99azYKGkohNhsXJuK2pQS32c-I2PW8Wu\",\"e\":\"AQAB\"}";
    var key = new JsonWebKey(jwk);
  }
}
