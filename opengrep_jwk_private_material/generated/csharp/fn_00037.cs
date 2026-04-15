using Microsoft.IdentityModel.Tokens;
public class Fixture {
  public void Run() {
    // JWK_PAYLOAD: {"kty":"RSA","kid":"-2CfbPTVg2oX","alg":"RS256","n":"kyAK3t6_ZEhk-F66bYVwMbu9OOrdY1UBE_gdgbUNQsSAhf4L","e":"AQAB"}
    var jwk = "{\"kty\":\"RSA\",\"kid\":\"-2CfbPTVg2oX\",\"alg\":\"RS256\",\"n\":\"kyAK3t6_ZEhk-F66bYVwMbu9OOrdY1UBE_gdgbUNQsSAhf4L\",\"e\":\"AQAB\"}";
    var key = new JsonWebKey(jwk);
  }
}
